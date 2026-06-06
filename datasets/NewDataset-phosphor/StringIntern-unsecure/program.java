import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class program {

    public static int foo(int h) {
        h = MultiTainter.taintedInt(h, "h_"); // @Phosphor
        int ret;
        ret = h;
        return ret;
    }

}