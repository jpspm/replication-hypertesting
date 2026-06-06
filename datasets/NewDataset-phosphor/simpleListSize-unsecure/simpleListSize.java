import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class simpleListSize {

    public static int listSizeLeak(int h) {
        h = MultiTainter.taintedInt(h, "h_"); // @Phosphor
        int ret;
        if (h < 10) {
            ret = h;
        } else {
            ret = 10;
        }
        return ret;
    }

}