import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class Eg4 {

    public static int f(int h, int l) {
        h = MultiTainter.taintedInt(h, "h_"); // @Phosphor
        int ret;
        ret = l + h;
        return ret;
    }

}