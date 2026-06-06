import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class simpleListSize {

    public static int listSizeLeak(int h) {
        h = MultiTainter.taintedInt(h, "h_"); // @Phosphor
        int r = 0;
        int ret;
        if (h < 10) {
            r = h;
        }
        ret = r;
        return ret;
    }

}